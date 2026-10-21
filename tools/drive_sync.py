"""Deterministic Drive source synchronization: drift, capture, cell delta and commit.

The client's Drive connector performs every live read. The `drive_inbox` hook
saves its raw metadata responses and workbook exports under `runs/drive_inbox/`;
this module works only on those saved files and on earlier captures, so every
step is reproducible offline. `data/source_sync.json` records, per watched
workbook, the Drive `modifiedTime` whose content the model has incorporated and
the export used as the cell-diff baseline. Stdlib only (system Python and hooks).
"""
import base64
import binascii
from collections import namedtuple
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tomllib
import zipfile
import xml.etree.ElementTree as ET

STATE = Path('data/source_sync.json')
INBOX = Path('runs/drive_inbox')
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
STATUS_WORDS = {'LOCKED', 'BASELINE', 'WORKING', 'OPEN', 'PROVISIONAL', 'SUPERSEDED',
                'DERIVED', 'DIAGNOSTIC', 'PROTOTYPE', 'EXPLORATORY', 'CANON', 'CANONICAL'}
# Spec sections whose change is architectural (class C) rather than local (A/B).
CORE_SECTIONS = {'ship', 'coordinates', 'layout', 'habitat', 'structure', 'propulsion',
                 'drive_manifold', 'eye', 'brow', 'radiators', 'shielding', 'hull', 'power',
                 'power_storage', 'rotor_interface', 'crew_transfer', 'configuration',
                 'realization', 'crew'}
CLASS_ORDER = ['NONE', 'EDITORIAL', 'A', 'B', 'C']
EXPORTABLE = ('sheet', 'xlsx_file')  # native Sheets export as xlsx; uploaded xlsx download as-is
MAX_MD_ITEMS = 40

Cell = namedtuple('Cell', 'raw value formula source_formula', defaults=(None,))
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def parse_utc(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00')) if text else None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def column_index(letters):
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value


def column_letters(index):
    letters = ''
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def split_ref(ref):
    match = re.fullmatch(r'\$?([A-Z]+)\$?(\d+)', ref.strip().upper())
    if not match:
        raise ValueError(f'not an A1 cell: {ref!r}')
    return int(match[2]), column_index(match[1])


def cell_name(row, col):
    return f'{column_letters(col)}{row}'


def parse_ranges(text):
    """A1 ranges such as 'A4:G5,A9:G9' -> [(row1, col1, row2, col2)]; 'A:C'/'4:9' open-ended."""
    rects = []
    for part in re.split(r'[,;]', text):
        part = part.strip().split('!')[-1].replace('$', '').upper()
        if not part:
            continue
        ends = part.split(':')
        if len(ends) == 1:
            ends *= 2
        bounds = []
        for end in ends:
            match = re.fullmatch(r'([A-Z]*)(\d*)', end)
            if not match or not (match[1] or match[2]):
                raise ValueError(f'unsupported range {text!r}')
            bounds.append((int(match[2]) if match[2] else None,
                           column_index(match[1]) if match[1] else None))
        (r1, c1), (r2, c2) = bounds
        rects.append((r1 or 1, c1 or 1, r2 or 10**7, c2 or 16384))
    return rects


def in_rects(row, col, rects):
    return any(r1 <= row <= r2 and c1 <= col <= c2 for r1, c1, r2, c2 in rects)


def normalize_formula(text):
    if not text:
        return None
    text = text.strip().lstrip('=').replace('_xlfn.', '').replace('_xlws.', '')
    return re.sub(r'\s+', '', text)


def number_or_text(raw):
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return raw.strip() if isinstance(raw, str) else raw
    return number if math.isfinite(number) else raw


def read_xlsx(data):
    """xlsx bytes -> {sheet: {(row, col): Cell}} in workbook order.

    `raw` keeps the stored text used by the historical `.txt` dumps. Shared-formula
    children carry no formula text in the file, so they compare by value only.
    """
    archive = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', NS):
            shared.append(''.join(t.text or '' for t in item.iter(f'{{{NS["m"]}}}t')))
    workbook = ET.fromstring(archive.read('xl/workbook.xml'))
    rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    targets = {rel.get('Id'): rel.get('Target') for rel in rels}
    sheets = {}
    for sheet in workbook.find('m:sheets', NS):
        target = targets[sheet.get(f'{{{NS["r"]}}}id')]
        path = 'xl/' + target.lstrip('/').replace('xl/', '')
        cells = {}
        for cell in ET.fromstring(archive.read(path)).iter(f'{{{NS["m"]}}}c'):
            kind, value, formula = cell.get('t'), cell.find('m:v', NS), cell.find('m:f', NS)
            if kind == 's' and value is not None:
                raw = shared[int(value.text)]
            elif kind == 'inlineStr':
                raw = ''.join(t.text or '' for t in cell.iter(f'{{{NS["m"]}}}t'))
            else:  # an empty <v/> prints as 'None', exactly like the historical dumps
                raw = f'{value.text}' if value is not None else ''
            formula_text = formula.text if formula is not None and formula.text else None
            if raw == '' and not formula_text:
                continue
            text = '' if value is not None and value.text is None and kind not in ('s', 'inlineStr') else raw
            if kind in ('s', 'inlineStr', 'str'):
                normalized = text.strip()
            elif kind == 'b':
                normalized = text == '1'
            elif kind == 'e':
                normalized = f'#ERROR {text}'
            else:
                normalized = number_or_text(text)
            cells[split_ref(cell.get('r'))] = Cell(raw, normalized, normalize_formula(formula_text),
                                                   formula_text)
        sheets[sheet.get('name')] = cells
    return sheets


def read_grid(response):
    """Sheets API grid data (one response or a list of saved entries) -> sheet cells."""
    sheets = {}
    entries = response if isinstance(response, list) else [response]
    for entry in entries:
        body = entry.get('response', entry)
        body = body.get('structuredContent', body)
        for sheet in body.get('sheets', []):
            cells = sheets.setdefault(sheet['properties']['title'], {})
            for block in sheet.get('data', []):
                row0, col0 = block.get('startRow', 0), block.get('startColumn', 0)
                for r, row in enumerate(block.get('rowData', [])):
                    for c, value in enumerate(row.get('values', [])):
                        effective = value.get('effectiveValue', {})
                        formula = value.get('userEnteredValue', {}).get('formulaValue')
                        if 'numberValue' in effective:
                            normalized = float(effective['numberValue'])
                            raw = repr(normalized)
                        elif 'boolValue' in effective:
                            normalized = raw = effective['boolValue']
                        elif 'stringValue' in effective:
                            raw = effective['stringValue']
                            normalized = raw.strip()
                        elif 'errorValue' in effective:
                            raw = normalized = f'#ERROR {effective["errorValue"].get("type")}'
                        else:
                            continue
                        cells[(row0 + r + 1, col0 + c + 1)] = Cell(str(raw), normalized,
                                                                    normalize_formula(formula),
                                                                    formula.lstrip('=') if formula else None)
    return sheets


def dump_text(sheets):
    """Same greppable format as the historical captures' dump_xlsx.py."""
    lines = []
    for name, cells in sheets.items():
        lines.append(f'\n===== SHEET {name} =====')
        row_cells = {}
        for (row, col), cell in sorted(cells.items()):
            text = f'{cell.raw} [={cell.source_formula}]' if cell.source_formula else cell.raw
            row_cells.setdefault(row, []).append(f'{cell_name(row, col)}={text}')
        lines.extend(' | '.join(parts) for parts in row_cells.values())
    return '\n'.join(lines) + '\n'


def load_baseline(root, baseline):
    path = root / baseline['path']
    if baseline['kind'] == 'xlsx':
        return read_xlsx(path.read_bytes())
    if baseline['kind'] == 'grid_json':
        return read_grid(json.loads(path.read_text()))
    raise ValueError(f'unknown baseline kind {baseline["kind"]!r}')


# ---------------------------------------------------------------- delta

def display(value, limit=160):
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= limit else text[:limit - 1] + '…'


def text_key(value):
    return re.sub(r'\s+', ' ', str(value)).strip().casefold()


def editorial_key(value):
    """Text equal up to case, spacing, dashes, quotes and trailing punctuation."""
    text = text_key(value)
    text = re.sub('[‒-―−]', '-', text)
    text = re.sub('[‘’“”`\'"]', '', text)
    return re.sub(r'[\s.,;:]+$', '', text)


def status_words(value):
    return {word for word in re.findall(r'[A-Z]{4,}', str(value)) if word in STATUS_WORDS}


def short_precision(raw):
    # Drive's xlsx export stores some cached results with six significant digits.
    return bool(re.fullmatch(r'-?\d(\.\d{1,5})?[eE][+-]?\d+', str(raw).strip()))


def same_value(first, second, loose=False):
    if isinstance(first, float) and isinstance(second, float):
        return math.isclose(first, second, rel_tol=1e-5 if loose else 1e-9, abs_tol=1e-12)
    return first == second


def compare_cells(old, new):
    """Return a change kind, or None when the cells are equivalent. Empty results count as absent."""
    old = old if old is not None and old.value != '' else None
    new = new if new is not None and new.value != '' else None
    if old is None and new is None:
        return None
    if old is None:
        return 'added'
    if new is None:
        return 'removed'
    if same_value(old.value, new.value, short_precision(old.raw) or short_precision(new.raw)):
        if old.formula and new.formula and old.formula != new.formula:
            return 'formula'
        return None
    if status_words(old.value) != status_words(new.value):
        return 'status'
    if isinstance(old.value, float) and isinstance(new.value, float):
        return 'numeric'
    if isinstance(old.value, str) and isinstance(new.value, str) \
            and editorial_key(old.value) == editorial_key(new.value):
        return 'editorial'
    if isinstance(old.value, float) or isinstance(new.value, float):
        return 'numeric'
    return 'text'


def row_label(cells, row):
    for col in (1, 2, 3):
        cell = cells.get((row, col))
        if cell and isinstance(cell.value, str) and cell.value:
            return display(cell.value, 60)
    return ''


def row_keys(cells):
    rows = sorted({row for row, _ in cells})
    keys = []
    for row in rows:
        values = [cells[(row, col)].value for col in (1, 2, 3) if (row, col) in cells]
        if not values:
            values = [cells[min(k for k in cells if k[0] == row)].value]
        keys.append(text_key(values[0]))
    return rows, keys


def align_rows(old_cells, new_cells):
    """Map old row numbers to new ones by their key column (ID or label)."""
    old_rows, old_keys = row_keys(old_cells)
    new_rows, new_keys = row_keys(new_cells)
    mapping, added = {}, []
    matcher = difflib.SequenceMatcher(None, old_keys, new_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        pairs = min(i2 - i1, j2 - j1) if tag in ('equal', 'replace') else 0
        for offset in range(pairs):
            mapping[old_rows[i1 + offset]] = new_rows[j1 + offset]
        added.extend(new_rows[j1 + pairs:j2])
    return mapping, added


def sheet_changes(sheet, old_cells, new_cells):
    mapping, added_rows = align_rows(old_cells, new_cells)
    changes = []

    def record(kind, old_ref, new_ref, old_cell, new_cell, label):
        changes.append({'sheet': sheet, 'kind': kind, 'cell': new_ref or old_ref, 'old_cell': old_ref,
                        'new_pos': split_ref(new_ref) if new_ref else None,
                        'old_pos': split_ref(old_ref) if old_ref else None, 'label': label,
                        'old': display(old_cell.value) if old_cell else None,
                        'new': display(new_cell.value) if new_cell else None})

    old_by_row, new_by_row = {}, {}
    for (row, col), cell in old_cells.items():
        old_by_row.setdefault(row, {})[col] = cell
    for (row, col), cell in new_cells.items():
        new_by_row.setdefault(row, {})[col] = cell
    for old_row, cols in sorted(old_by_row.items()):
        new_row = mapping.get(old_row)
        if new_row is None:
            record('row_removed', cell_name(old_row, 1), None,
                   Cell('', ' | '.join(str(c.value) for c in cols.values()), None), None,
                   row_label(old_cells, old_row))
            continue
        new_cols = new_by_row.get(new_row, {})
        label = row_label(new_cells, new_row) or row_label(old_cells, old_row)
        for col in sorted(set(cols) | set(new_cols)):
            kind = compare_cells(cols.get(col), new_cols.get(col))
            if kind:
                record(kind, cell_name(old_row, col) if col in cols else None,
                       cell_name(new_row, col) if col in new_cols else None,
                       cols.get(col), new_cols.get(col), label)
    for new_row in added_rows:
        cols = new_by_row[new_row]
        record('row_added', None, cell_name(new_row, 1), None,
               Cell('', ' | '.join(str(c.value) for c in cols.values()), None),
               row_label(new_cells, new_row))
    return changes, mapping


def spec_node(spec, path):
    node = spec
    for part in re.findall(r'[^.\[\]]+|\[\d+\]', path):
        if part.startswith('['):
            node = node[int(part[1:-1])]
        else:
            node = node[part]
    return node


def spec_summary(spec, path):
    """Scalar fields of the table owning a `source_ref` / `evidence_ref`."""
    parent = path.rsplit('.', 1)[0]
    try:
        node = spec_node(spec, parent)
    except (KeyError, IndexError, TypeError):
        return {}
    if not isinstance(node, dict):
        return {}
    summary = {}
    for key, value in node.items():
        if key in ('source_ref', 'evidence_ref', 'notes', 'rationale', 'note'):
            continue
        if isinstance(value, (int, float, bool)) or (isinstance(value, str) and len(value) <= 60):
            summary[key] = value
        if len(summary) >= 8:
            break
    return summary


def spec_numbers(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [n for child in value.values() for n in spec_numbers(child)]
    if isinstance(value, list):
        return [n for child in value for n in spec_numbers(child)]
    return []


def matches_any(number, numbers):
    return any(math.isclose(number, other, rel_tol=1e-6, abs_tol=1e-9) for other in numbers)


def workbook_delta(root, key, entry, new_sheets, sources, consumers, spec):
    """Cell-level delta for one workbook against its recorded baseline."""
    baseline = entry.get('baseline')
    result = {'key': key, 'title': entry['title'], 'role': entry['role'], 'baseline': baseline,
              'reviewed_sheets': sorted({r.rpartition('!')[0].strip("'") for r in entry.get('reviewed_ranges', [])}),
              'baseline_stale': is_stale(entry), 'sheets_added': [], 'sheets_removed': [],
              'sheets_renamed': [], 'changes': [], 'records': [], 'range_drift': []}
    if not baseline:
        result['no_baseline'] = True
        result['sheets_added'] = list(new_sheets)
        return result
    old_sheets = load_baseline(root, baseline)
    baseline_rects = {}
    for text in baseline.get('ranges', []):
        sheet, _, rng = text.rpartition('!')
        baseline_rects.setdefault(sheet.strip("'"), []).extend(parse_ranges(rng))
    removed = [s for s in old_sheets if s not in new_sheets]
    added = [s for s in new_sheets if s not in old_sheets]
    if baseline_rects:  # partial baseline: only its sheets can be compared or reported removed
        removed = []
        added = [s for s in added if s not in baseline_rects]
    for old in list(removed):
        old_keys = row_keys(old_sheets[old])[1]
        for new in list(added):
            ratio = difflib.SequenceMatcher(None, old_keys, row_keys(new_sheets[new])[1]).ratio()
            if ratio >= 0.8:
                result['sheets_renamed'].append({'old': old, 'new': new, 'similarity': round(ratio, 3)})
                removed.remove(old)
                added.remove(new)
                break
    result['sheets_added'], result['sheets_removed'] = added, removed
    reviewed = {}
    for text in entry.get('reviewed_ranges', []):
        sheet, _, rng = text.rpartition('!')
        reviewed.setdefault(sheet.strip("'"), []).extend(parse_ranges(rng))
    pairs = [(s, s) for s in old_sheets if s in new_sheets]
    pairs += [(r['old'], r['new']) for r in result['sheets_renamed']]
    row_maps = {}
    for old_name, new_name in pairs:
        old_cells, new_cells = old_sheets[old_name], new_sheets[new_name]
        rects = baseline_rects.get(old_name)
        if baseline_rects and rects is None:
            continue
        if rects:
            new_cells = {pos: c for pos, c in new_cells.items() if in_rects(*pos, rects)}
        changes, row_maps[old_name] = sheet_changes(new_name, old_cells, new_cells)
        for change in changes:
            change['covered_by_review'] = bool(change['new_pos'] and
                                               in_rects(*change['new_pos'], reviewed.get(new_name, [])))
        result['changes'].extend(changes)
    renamed = {r['old']: r['new'] for r in result['sheets_renamed']}
    by_sheet = {}
    for index, change in enumerate(result['changes']):
        by_sheet.setdefault(change['sheet'], []).append(index)
    for ident, source in sources.items():
        if source.get('workbook_id') != entry['id']:
            continue
        sheet = source['sheet']
        # The primary range plus any "<sheet>!<range>" cross_ranges carrying the same evidence on other sheets.
        targets = [(sheet, source['range'])] + [tuple(r.split('!', 1)) for r in source.get('cross_ranges', [])]
        hits, drift = [], False
        for target, text in targets:
            rects = parse_ranges(text)
            hits += [i for i in by_sheet.get(renamed.get(target, target), []) if i not in hits
                     and any(p and in_rects(*p, rects) for p in (result['changes'][i]['old_pos'],
                                                                 result['changes'][i]['new_pos']))]
            if target in row_maps and target in old_sheets:
                rows = sorted({r for r, c in old_sheets[target] if in_rects(r, c, rects)})
                drift = drift or any(row_maps[target].get(r) != r for r in rows)
            if target in result['sheets_removed'] or target in renamed:
                drift = True
        if drift:
            result['range_drift'].append({'source_id': ident, 'sheet': sheet, 'range': source['range']})
        if not hits and not drift:
            continue
        params = consumers.get(ident, [])
        values = {p.rsplit('.', 1)[0]: spec_summary(spec, p) for p in params}
        numbers = [n for v in values.values() for n in spec_numbers(v)]
        stale_spec = False
        for i in hits:
            change = result['changes'][i]
            change.setdefault('source_ids', []).append(ident)
            if change['kind'] == 'numeric':
                old, new = number_or_text(change['old']), number_or_text(change['new'])
                if isinstance(old, float) and isinstance(new, float) \
                        and matches_any(old, numbers) and not matches_any(new, numbers):
                    change['spec_matches_old_value'] = stale_spec = True
        result['records'].append({'source_id': ident, 'canon_status': source.get('canon_status'),
                                  'sheet': sheet, 'range': source['range'], 'changes': hits,
                                  'range_drift': drift, 'parameter_refs': params,
                                  'spec_values': values, 'spec_matches_old_value': stale_spec})
    return result


def substantive(change):
    return change['kind'] not in ('editorial', 'formula')


def suggest_class(workbooks):
    """Deterministic lower bound for the coordinator's classification, with reasons."""
    level, reasons = 'NONE', []

    def raise_to(target, reason):
        nonlocal level
        if CLASS_ORDER.index(target) > CLASS_ORDER.index(level):
            level = target
        reasons.append(f'{target}: {reason}')

    for wb in workbooks:
        name, role = wb['key'], wb['role']
        if wb.get('no_baseline'):
            if wb.get('unchanged_since_review'):
                reasons.append(f'NONE: {name}: first cell baseline for unchanged content')
            else:
                raise_to('B', f'{name}: changed without a cell baseline; review content')
            continue
        cap = role in ('reference', 'correspondence')
        if any(c['kind'] == 'editorial' or c['kind'] == 'formula' for c in wb['changes']):
            raise_to('EDITORIAL', f'{name}: editorial/formula-only edits')
        for record in wb['records']:
            changes = [wb['changes'][i] for i in record['changes']]
            real = [c for c in changes if substantive(c)]
            sections = {p.split('.')[0].split('[')[0] for p in record['parameter_refs']}
            label = f'{name}: {record["source_id"]} ({record["canon_status"]})'
            if record['spec_matches_old_value']:
                raise_to('C' if sections & CORE_SECTIONS else 'B', f'{label} spec still holds the OLD value')
            if record['range_drift']:
                raise_to('B', f'{label} range drift; source_map range needs review')
            real = [c for c in real if not c.get('covered_by_review')]
            if not real:
                continue
            if cap:
                raise_to('B', f'{label} changed in a {role} workbook (review only)')
            elif record['canon_status'] == 'LOCKED' or any(c['kind'] in ('status', 'row_removed') for c in real):
                raise_to('C', f'{label} LOCKED/status/removed-row change')
            elif sections & CORE_SECTIONS and any(c['kind'] == 'numeric' for c in real):
                raise_to('C', f'{label} numeric change in core section(s) {sorted(sections & CORE_SECTIONS)}')
            elif len(record['parameter_refs']) <= 1:
                raise_to('A', f'{label} isolated change')
            else:
                raise_to('B', f'{label} change feeds {len(record["parameter_refs"])} parameters')
        unmapped = [c for c in wb['changes'] if substantive(c) and not c.get('source_ids')
                    and not c.get('covered_by_review')]
        weighty = [c for c in unmapped if c['kind'] in ('numeric', 'status', 'row_added', 'row_removed')]
        if weighty and role in ('owner', 'routing'):
            raise_to('B', f'{name}: {len(weighty)} unmapped numeric/status/row changes need routing review')
        elif unmapped:
            raise_to('A' if not cap else 'EDITORIAL', f'{name}: {len(unmapped)} unmapped text changes')
        reviewed_sheets = set(wb.get('reviewed_sheets', ()))
        structural = [s for s in wb['sheets_added'] if s not in reviewed_sheets] + wb['sheets_removed'] \
            + [r['new'] for r in wb['sheets_renamed']]
        if structural and not cap:
            raise_to('B', f'{name}: sheets added/removed/renamed: {structural[:5]}')
    mapped_sections = {p.split('.')[0].split('[')[0] for wb in workbooks for r in wb['records']
                       if any(substantive(wb['changes'][i]) for i in r['changes'])
                       for p in r['parameter_refs']}
    if len(mapped_sections & CORE_SECTIONS) >= 3:
        raise_to('C', f'changes span core sections {sorted(mapped_sections & CORE_SECTIONS)}')
    return level, reasons


# ---------------------------------------------------------------- state, drift, capture

def load_state(root):
    return json.loads((root / STATE).read_text())


def save_state(root, state):
    (root / STATE).write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n')


def is_stale(entry):
    baseline = entry.get('baseline')
    if not baseline:
        return True
    return parse_utc(baseline['modified_utc']) < parse_utc(entry['reviewed_modified_utc'])


def metadata_records(value):
    """Yield {id, title, modified, mimeType} from any saved metadata/search response."""
    if isinstance(value, str):
        if len(value) > 200_000:
            return
        try:
            value = json.loads(value)
        except ValueError:
            return
    if isinstance(value, list):
        for child in value:
            yield from metadata_records(child)
    elif isinstance(value, dict):
        modified = value.get('modifiedTime') or value.get('modified_time')
        if value.get('id') and modified:
            yield {'id': value['id'], 'title': value.get('title') or value.get('name'),
                   'modified': modified, 'mimeType': value.get('mimeType') or value.get('mime_type')}
        for key in ('structuredContent', 'files', 'content', 'response', 'text'):
            if isinstance(value.get(key), (list, dict)) or key == 'text':
                yield from metadata_records(value.get(key))


def observed(root, since=None):
    """Latest observed metadata per file ID from the inbox, optionally after `since`."""
    latest = {}
    limit = parse_utc(since) if since else None
    for path in sorted((root / INBOX).glob('meta-*.json')):
        saved = json.loads(path.read_text())
        at = parse_utc(saved['saved_at'])
        if limit and at < limit:
            continue
        for record in metadata_records(saved['response']):
            record['observed_at'] = saved['saved_at']
            previous = latest.get(record['id'])
            if not previous or parse_utc(previous['observed_at']) <= at:
                latest[record['id']] = record
    return latest


def drift(root, since=None):
    state = load_state(root)
    seen = observed(root, since)
    watched = {entry['id'] for entry in state['workbooks'].values()}
    report = {'changed': [], 'baseline_refresh': [], 'unobserved': [], 'unchanged': [],
              'new_files': []}
    for key, entry in state['workbooks'].items():
        record = seen.get(entry['id'])
        if not record:
            report['unobserved'].append(key)
            continue
        modified = parse_utc(record['modified'])
        item = {'key': key, 'id': entry['id'], 'reviewed': entry['reviewed_modified_utc'],
                'observed': record['modified'], 'role': entry['role']}
        if modified > parse_utc(entry['reviewed_modified_utc']):
            report['changed'].append(item)
        elif is_stale(entry) and entry['kind'] in EXPORTABLE:
            report['baseline_refresh'].append(item)
        else:
            report['unchanged'].append(key)
    # Files modified before the last reviewed read were visible to that review's TOC routing.
    horizon = parse_utc(state.get('last_successful_sync_utc') or state.get('seeded', {}).get('reviewed_at_utc')
                        or min(e['reviewed_modified_utc'] for e in state['workbooks'].values()))
    for ident, record in seen.items():
        title = record.get('title') or ''
        if ident not in watched and 'IGNITION' in title.upper() and parse_utc(record['modified']) > horizon:
            report['new_files'].append({'id': ident, 'title': title, 'modified': record['modified']})
    report['export'] = [i['key'] for i in report['changed'] + report['baseline_refresh']
                        if state['workbooks'][i['key']]['kind'] in EXPORTABLE]
    return report


def inbox_exports(root, since=None):
    """Hook-saved workbook exports: {file_id: newest export metadata}."""
    newest = {}
    limit = parse_utc(since) if since else None
    for path in sorted((root / INBOX).glob('export-*.json')):
        meta = json.loads(path.read_text())
        if limit and parse_utc(meta['saved_at']) < limit:
            continue
        meta['xlsx_path'] = str(path.with_suffix('.xlsx'))
        if meta['fileId'] not in newest or meta['saved_at'] >= newest[meta['fileId']]['saved_at']:
            newest[meta['fileId']] = meta
    return newest


def _is_file(text):
    """Path.is_file() that treats an over-long name as "not a file" (Python 3.13 raises ENAMETOOLONG)."""
    try:
        return Path(text).is_file()
    except OSError:
        return False


def export_bytes(response):
    """Decode a download_file_content response (dict, JSON text, content blocks or a
    persisted tool-results file) into (bytes, metadata)."""
    if isinstance(response, Path) or (isinstance(response, str) and len(response) < 4096
                                      and '\n' not in response and _is_file(response)):
        path = Path(response)
        if path.read_bytes()[:2] == b'PK':
            return path.read_bytes(), {}
        response = path.read_text()
    if isinstance(response, str):
        persisted = re.search(r'saved to (/\S+?\.(?:txt|json))\b', response)
        if persisted and len(response) < 20_000:  # oversized result the client wrote to disk
            return export_bytes(Path(persisted[1]))
        try:
            response = json.loads(response)
        except ValueError:
            return None, {}
    if isinstance(response, list):
        for child in response:
            data, meta = export_bytes(child)
            if data:
                return data, meta
    elif isinstance(response, dict):
        content = response.get('content')
        if isinstance(content, str) and len(content) > 64:
            try:
                return base64.b64decode(content, validate=True), {
                    k: response.get(k) for k in ('id', 'title', 'mimeType')}
            except (ValueError, binascii.Error):
                pass
        for key in ('structuredContent', 'content', 'text', 'result'):
            child = response.get(key)
            if isinstance(child, (list, dict)) or (key == 'text' and isinstance(child, str)):
                data, meta = export_bytes(child)
                if data:
                    return data, meta
    return None, {}


def write_new(path, data):
    if path.exists():
        raise FileExistsError(f'refusing to overwrite capture evidence {path}')
    path.write_bytes(data if isinstance(data, bytes) else data.encode())


def capture(root, capture_dir, since=None, keys=None, files=()):
    """Copy hook-saved exports (or explicit files `key=path`) into an evidence capture."""
    state = load_state(root)
    capture_dir = root / capture_dir if not Path(capture_dir).is_absolute() else Path(capture_dir)
    capture_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = capture_dir / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        'captured_on': utc_now()[:10], 'status': 'open',
        'method': 'Drive connector download_file_content (xlsx export) saved by '
                  'tools/hooks/drive_inbox.py; dumps and hashes by tools/drive_sync.py',
        'workbooks': {}, 'metadata_before': {}}
    if manifest.get('status') != 'open':
        raise ValueError(f'{manifest_path} is {manifest.get("status")}; use a new capture directory')
    by_id = {entry['id']: key for key, entry in state['workbooks'].items()}
    seen = observed(root)
    sources = []
    for pair in files:
        key, _, path = pair.partition('=')
        data, _ = export_bytes(Path(path))
        if not data:
            raise ValueError(f'{path}: no workbook export found')
        sources.append((key, data, {'saved_at': utc_now(), 'fileId': state['workbooks'][key]['id']}))
    for file_id, meta in inbox_exports(root, since).items():
        key = by_id.get(file_id)
        if key and (not keys or key in keys):
            sources.append((key, Path(meta['xlsx_path']).read_bytes(), meta))
    if not sources:
        raise ValueError('no workbook exports found; download them through the connector first')
    written = []
    for key, data, meta in sources:
        entry = state['workbooks'][key]
        sheets = read_xlsx(data)
        text = dump_text(sheets)
        write_new(capture_dir / f'{key}.xlsx', data)
        write_new(capture_dir / f'{key}.txt', text)
        before = seen.get(entry['id'])
        manifest['metadata_before'][entry['id']] = before
        manifest['workbooks'][key] = {
            'title': entry['title'], 'id': entry['id'], 'role': entry['role'],
            'drive_modified_utc': before['modified'] if before else None,
            'exported_at_utc': meta['saved_at'], 'xlsx': f'{key}.xlsx', 'xlsx_sha256': sha256(data),
            'text': f'{key}.txt', 'text_sha256': sha256(text.encode()), 'sheets': len(sheets)}
        written.append(key)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return {'capture': str(capture_dir.relative_to(root)) if capture_dir.is_relative_to(root) else str(capture_dir),
            'workbooks': written}


def parameter_consumers(spec):
    import workflow  # local import keeps hooks free of the spec loader
    consumers = {}
    for ref, path in workflow.parameter_refs(spec):
        consumers.setdefault(ref, []).append(path)
    return consumers


def delta(root, capture_dir):
    capture_dir = root / capture_dir if not Path(capture_dir).is_absolute() else Path(capture_dir)
    manifest = json.loads((capture_dir / 'manifest.json').read_text())
    state = load_state(root)
    spec = tomllib.loads((root / 'data/wayfarer_3d.toml').read_text())
    sources = tomllib.loads((root / 'data/source_map.toml').read_text())['sources']
    consumers = parameter_consumers(spec)
    workbooks = []
    for key, info in manifest['workbooks'].items():
        new_sheets = read_xlsx((capture_dir / info['xlsx']).read_bytes())
        entry = state['workbooks'][key]
        wb = workbook_delta(root, key, entry, new_sheets, sources, consumers, spec)
        wb['drive_modified_utc'] = info.get('drive_modified_utc')
        wb['unchanged_since_review'] = bool(info.get('drive_modified_utc')) and \
            parse_utc(info['drive_modified_utc']) <= parse_utc(entry['reviewed_modified_utc'])
        workbooks.append(wb)
    level, reasons = suggest_class(workbooks)
    result = {'capture': str(capture_dir), 'computed_at': utc_now(), 'suggested_class': level,
              'reasons': reasons, 'workbooks': workbooks}
    (capture_dir / 'delta.json').write_text(json.dumps(result, indent=1, ensure_ascii=False) + '\n')
    (capture_dir / 'delta.md').write_text(delta_markdown(result))
    return result


def delta_summary(result):
    rows = []
    for wb in result['workbooks']:
        real = [c for c in wb['changes'] if substantive(c)]
        rows.append({'workbook': wb['key'], 'role': wb['role'], 'baseline_stale': wb['baseline_stale'],
                     'no_baseline': wb.get('no_baseline', False), 'changes': len(wb['changes']),
                     'substantive': len(real),
                     'covered_by_review': sum(1 for c in real if c.get('covered_by_review')),
                     'mapped_records': len(wb['records']), 'range_drift': len(wb['range_drift']),
                     'sheets': {'added': len(wb['sheets_added']), 'removed': len(wb['sheets_removed']),
                                'renamed': len(wb['sheets_renamed'])}})
    return {'suggested_class': result['suggested_class'], 'reasons': result['reasons'][:12],
            'workbooks': rows, 'detail': str(Path(result['capture']) / 'delta.md')}


def delta_markdown(result):
    lines = [f'# Source delta', '',
             f'Capture `{result["capture"]}`, computed {result["computed_at"]}. Full detail: `delta.json`.',
             f'Deterministic lower bound for classification: **{result["suggested_class"]}**.', '']
    lines += [f'- {r}' for r in result['reasons'][:20]]
    lines += ['', '| workbook | role | baseline | substantive | covered by review | mapped records | range drift | sheets +/-/renamed |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for wb, row in zip(result['workbooks'], delta_summary(result)['workbooks']):
        base = 'none' if wb.get('no_baseline') else ('stale ' if wb['baseline_stale'] else '') + (Path(wb['baseline']['path']).parent.name or wb['baseline']['path'])
        lines.append(f'| {wb["key"]} | {wb["role"]} | {base} | {row["substantive"]} | {row["covered_by_review"]} | '
                     f'{row["mapped_records"]} | {row["range_drift"]} | {len(wb["sheets_added"])}/{len(wb["sheets_removed"])}/{len(wb["sheets_renamed"])} |')
    for wb in result['workbooks']:
        lines += ['', f'## {wb["title"]} ({wb["role"]})']
        if wb['baseline_stale'] and wb.get('baseline'):
            lines.append(f'Baseline export predates the reviewed state ({wb["baseline"]["modified_utc"]}); '
                         'changes marked *reviewed* fall inside ranges read in the last review.')
        if wb.get('no_baseline'):
            if wb.get('unchanged_since_review'):
                lines.append('No cell baseline existed; Drive is unchanged since the last review, so this capture only becomes the baseline.')
            else:
                lines.append('Changed, with no cell baseline to diff against. Review sheets relevant to Wayfarer: '
                             + ', '.join(wb['sheets_added'][:30]))
            continue
        for label, items in (('Sheets added', wb['sheets_added']), ('Sheets removed', wb['sheets_removed'])):
            if items:
                lines.append(f'- {label}: ' + ', '.join(items))
        for item in wb['sheets_renamed']:
            lines.append(f'- Sheet renamed: {item["old"]} → {item["new"]}')
        for item in wb['range_drift'][:MAX_MD_ITEMS]:
            lines.append(f'- Range drift: `{item["source_id"]}` {item["sheet"]}!{item["range"]}')
        if wb['records']:
            lines.append('')
            lines.append('Mapped source records:')
        for record in wb['records'][:MAX_MD_ITEMS]:
            flag = ' — **spec still holds the OLD value**' if record['spec_matches_old_value'] else ''
            lines.append(f'- `{record["source_id"]}` ({record["canon_status"]}) {record["sheet"]}!{record["range"]}{flag}')
            if record['spec_values']:
                lines.append('  - spec: ' + '; '.join(f'`{p}` {json.dumps(v, ensure_ascii=False)}'
                                                      for p, v in list(record['spec_values'].items())[:4]))
            for i in record['changes'][:8]:
                lines.append('  - ' + change_line(wb['changes'][i]))
        unmapped = [c for c in wb['changes'] if substantive(c) and not c.get('source_ids')]
        fresh = [c for c in unmapped if not c.get('covered_by_review')]
        if fresh:
            lines += ['', f'Unmapped substantive changes ({len(fresh)}):']
            lines += ['- ' + change_line(c) for c in fresh[:MAX_MD_ITEMS]]
            if len(fresh) > MAX_MD_ITEMS:
                lines.append(f'- … {len(fresh) - MAX_MD_ITEMS} more in delta.json')
        covered = len(unmapped) - len(fresh)
        minor = sum(1 for c in wb['changes'] if not substantive(c))
        if covered or minor:
            lines.append(f'\n{covered} unmapped changes inside previously reviewed ranges; '
                         f'{minor} editorial/formula-only edits (see delta.json).')
    return '\n'.join(lines) + '\n'


def change_line(change):
    where = f'{change["sheet"]}!{change["cell"]}'
    if change['old_cell'] and change['old_cell'] != change['cell']:
        where += f' (was {change["old_cell"]})'
    label = f' [{change["label"]}]' if change['label'] else ''
    tail = ' *reviewed*' if change.get('covered_by_review') else ''
    return f'{where}{label} {change["kind"]}: {change["old"]!s} → {change["new"]!s}{tail}'


def commit(root, capture_dir, workbooks=None, note=None):
    """Record the capture's workbook versions as incorporated into the model data."""
    capture_dir = root / capture_dir if not Path(capture_dir).is_absolute() else Path(capture_dir)
    manifest_path = capture_dir / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('status') != 'open':
        raise ValueError(f'capture is {manifest.get("status")}, not open')
    state = load_state(root)
    keys = workbooks or list(manifest['workbooks'])
    stamp = utc_now()
    rel = str(capture_dir.relative_to(root)) if capture_dir.is_relative_to(root) else str(capture_dir)
    for key in keys:
        info, entry = manifest['workbooks'][key], state['workbooks'][key]
        entry['reviewed_modified_utc'] = info['drive_modified_utc']
        entry['reviewed_in'] = rel + '/'
        entry['reviewed_ranges'] = []
        entry['baseline'] = {'kind': 'xlsx', 'path': f'{rel}/{info["xlsx"]}',
                             'modified_utc': info['drive_modified_utc']}
    state['last_successful_sync_utc'] = stamp
    state.setdefault('history', []).append({'at': stamp, 'capture': rel, 'workbooks': keys, 'note': note})
    state['history'] = state['history'][-20:]
    save_state(root, state)
    manifest['committed_workbooks'] = sorted(set(manifest.get('committed_workbooks', [])) | set(keys))
    if set(manifest['committed_workbooks']) >= set(manifest['workbooks']):
        manifest['status'] = 'committed'
    manifest['committed_at_utc'] = stamp
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return {'committed': keys, 'capture': rel, 'at': stamp}
