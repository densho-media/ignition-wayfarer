"""Drive sync: xlsx reading, cell delta semantics, class lower bound, drift, capture and commit gates."""
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import drive_sync as ds


def xlsx(sheets):
    """Minimal xlsx: {sheet: {'B2': value | (value, formula)}} with inline strings."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        names = list(sheets)
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' +
                         ''.join(f'<sheet name="{n}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(names)) +
                         '</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels',
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
                         ''.join(f'<Relationship Id="rId{i + 1}" Target="worksheets/sheet{i + 1}.xml"/>'
                                 for i in range(len(names))) + '</Relationships>')
        for i, name in enumerate(names):
            rows = {}
            for ref, value in sheets[name].items():
                rows.setdefault(ds.split_ref(ref)[0], []).append((ds.split_ref(ref)[1], ref, value))
            xml = []
            for row, cells in sorted(rows.items()):
                parts = []
                for _, ref, value in sorted(cells):
                    value, formula = value if isinstance(value, tuple) else (value, None)
                    f = f'<f>{formula}</f>' if formula else ''
                    if isinstance(value, str):
                        parts.append(f'<c r="{ref}" t="inlineStr">{f}<is><t>{value}</t></is></c>')
                    else:
                        parts.append(f'<c r="{ref}">{f}<v>{value}</v></c>')
                xml.append(f'<row r="{row}">{"".join(parts)}</row>')
            archive.writestr(f'xl/worksheets/sheet{i + 1}.xml',
                             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                             + ''.join(xml) + '</sheetData></worksheet>')
    return out.getvalue()


OLD = {'INPUTS': {'A1': 'Key', 'B1': 'Value', 'C1': 'Status',
                  'A2': 'ship_length_m', 'B2': 85, 'C2': 'BASELINE',
                  'A3': 'crew', 'B3': 6, 'C3': 'LOCKED',
                  'A4': 'note', 'B4': 'Radiators glowing — after burns', 'C4': 'WORKING'}}
SPEC = '[ship.length]\nvalue = 85\ncanon_status = "BASELINE"\nsource_ref = "ship_length"\n'
SOURCES = ('[sources.ship_length]\nworkbook_id = "wb1"\nsheet = "INPUTS"\nrange = "A2:C2"\ncanon_status = "BASELINE"\n'
           '[sources.crew]\nworkbook_id = "wb1"\nsheet = "INPUTS"\nrange = "A3:C3"\ncanon_status = "LOCKED"\n')


def entry(**extra):
    base = {'title': 'IGNITION — Test', 'id': 'wb1', 'role': 'owner', 'kind': 'sheet',
            'reviewed_modified_utc': '2026-09-28T00:00:00.000Z', 'reviewed_ranges': [],
            'baseline': {'kind': 'xlsx', 'path': 'old.xlsx', 'modified_utc': '2026-09-28T00:00:00.000Z'}}
    base.update(extra)
    return base


class DeltaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'old.xlsx').write_bytes(xlsx(OLD))
        import tomllib
        self.spec = tomllib.loads(SPEC)
        self.sources = tomllib.loads(SOURCES)['sources']
        self.consumers = ds.parameter_consumers(self.spec)

    def tearDown(self):
        self.temp.cleanup()

    def delta(self, new, **extra):
        return ds.workbook_delta(self.root, 'test', entry(**extra), ds.read_xlsx(xlsx(new)), self.sources,
                                 self.consumers, self.spec)

    def test_dump_matches_historical_format(self):
        text = ds.dump_text(ds.read_xlsx(xlsx({'S': {'A1': 'x', 'B1': (2, 'A2*2')}})))
        self.assertEqual(text, '\n===== SHEET S =====\nA1=x | B1=2 [=A2*2]\n')

    def test_numeric_change_flags_spec_still_holding_old_value(self):
        new = json.loads(json.dumps(OLD))
        new['INPUTS']['B2'] = 87
        wb = self.delta(new)
        record = wb['records'][0]
        self.assertEqual(record['source_id'], 'ship_length')
        self.assertTrue(record['spec_matches_old_value'])
        self.assertEqual(record['parameter_refs'], ['ship.length.source_ref'])
        level, reasons = ds.suggest_class([wb])
        self.assertEqual(level, 'C')
        self.assertTrue(any('OLD value' in r for r in reasons))

    def test_cross_ranges_map_changes_on_other_sheets(self):
        old = json.loads(json.dumps(OLD))
        old['CONTRACT'] = {'A1': 'REQ', 'B1': 'Answer', 'A2': 'G1', 'B2': 'length 80-90 m'}
        (self.root / 'old.xlsx').write_bytes(xlsx(old))
        self.sources['ship_length']['cross_ranges'] = ['CONTRACT!A2:B2']
        new = json.loads(json.dumps(old))
        new['CONTRACT']['B2'] = 'length 220-240 m'
        wb = self.delta(new)
        self.assertEqual([r['source_id'] for r in wb['records']], ['ship_length'])
        change = wb['changes'][wb['records'][0]['changes'][0]]
        self.assertEqual((change['sheet'], change['source_ids']), ('CONTRACT', ['ship_length']))

    def test_inserted_row_is_an_addition_and_range_drift_not_a_value_flood(self):
        new = {'INPUTS': {'A1': 'Key', 'B1': 'Value', 'C1': 'Status',
                          'A2': 'hull_margin_m', 'B2': 0.5, 'C2': 'PROTOTYPE',
                          'A3': 'ship_length_m', 'B3': 85, 'C3': 'BASELINE',
                          'A4': 'crew', 'B4': 6, 'C4': 'LOCKED',
                          'A5': 'note', 'B5': 'Radiators glowing — after burns', 'C5': 'WORKING'}}
        wb = self.delta(new)
        kinds = [c['kind'] for c in wb['changes']]
        self.assertEqual(kinds, ['row_added'])
        self.assertEqual({d['source_id'] for d in wb['range_drift']}, {'ship_length', 'crew'})
        self.assertEqual(ds.suggest_class([wb])[0], 'B')

    def test_editorial_status_and_equivalence_rules(self):
        new = json.loads(json.dumps(OLD))
        new['INPUTS']['B4'] = 'radiators glowing - after burns.'
        self.assertEqual([c['kind'] for c in self.delta(new)['changes']], ['editorial'])
        self.assertEqual(ds.suggest_class([self.delta(new)])[0], 'EDITORIAL')
        new['INPUTS']['C3'] = 'WORKING'
        wb = self.delta(new)
        self.assertIn('status', [c['kind'] for c in wb['changes']])
        self.assertEqual(ds.suggest_class([wb])[0], 'C')
        exported = ds.Cell('1.04347e+16', 1.04347e16, None)
        exact = ds.Cell('1.0434670248997704e+16', 1.0434670248997704e16, None)
        self.assertIsNone(ds.compare_cells(exported, exact))
        self.assertIsNone(ds.compare_cells(ds.Cell('None', '', 'IF(A1="","",1)'), None))

    def test_changes_inside_reviewed_ranges_do_not_raise_the_class(self):
        new = json.loads(json.dumps(OLD))
        new['INPUTS']['B2'] = 87
        self.sources['ship_length']['range'] = 'A9:C9'  # unmapped numeric change
        wb = self.delta(new, reviewed_ranges=['INPUTS!A1:C4'])
        self.assertTrue(wb['changes'][0]['covered_by_review'])
        self.assertEqual(ds.suggest_class([wb])[0], 'NONE')
        self.assertEqual(ds.suggest_class([self.delta(new)])[0], 'B')

    def test_reference_workbooks_are_review_only(self):
        new = json.loads(json.dumps(OLD))
        new['INPUTS']['B3'] = 7
        wb = self.delta(new, role='reference')
        self.assertEqual(ds.suggest_class([wb])[0], 'B')

    def test_persisted_oversized_result_is_decoded_from_its_file(self):
        data = xlsx(OLD)
        saved = self.root / 'tool-result.txt'
        saved.write_text(json.dumps({'content': base64.b64encode(data).decode(), 'id': 'wb1',
                                     'title': 'IGNITION — Test', 'mimeType': ds.XLSX_MIME}))
        message = f'Error: result (152,875 characters) exceeds maximum allowed tokens. Output has been saved to {saved}.\nFormat: JSON'
        decoded, meta = ds.export_bytes(message)
        self.assertEqual(decoded, data)
        self.assertEqual(meta['title'], 'IGNITION — Test')


class SyncStateTests(unittest.TestCase):
    """drift → capture → delta → commit on a disposable root."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        (self.root / 'data/wayfarer_3d.toml').write_text(SPEC)
        (self.root / 'data/source_map.toml').write_text(SOURCES)
        (self.root / 'old.xlsx').write_bytes(xlsx(OLD))
        state = {'schema': 1, 'last_successful_sync_utc': None, 'history': [],
                 'workbooks': {'test': entry(), 'ref': entry(id='wb2', role='reference', baseline=None,
                                                             reviewed_modified_utc='2026-09-20T00:00:00.000Z')}}
        ds.save_state(self.root, state)
        (self.root / ds.INBOX).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def observe(self, saved_at, **modified):
        response = json.dumps({'files': [{'id': i, 'title': f'IGNITION — {i}', 'modifiedTime': t}
                                         for i, t in modified.items()]})
        (self.root / ds.INBOX / f'meta-{saved_at.replace(":", "")}-x.json').write_text(
            json.dumps({'saved_at': saved_at, 'tool': 'search', 'response': response}))

    def export(self, saved_at, sheets):
        base = self.root / ds.INBOX / 'export-wb1-abc'
        base.with_suffix('.xlsx').write_bytes(xlsx(sheets))
        base.with_suffix('.json').write_text(json.dumps({'fileId': 'wb1', 'saved_at': saved_at}))

    def test_drift_reports_changed_unchanged_and_new_files(self):
        self.observe('2026-09-30T08:00:00.000Z', wb1='2026-09-29T12:00:00.000Z', wb2='2026-09-20T00:00:00.000Z',
                     wb9='2026-09-29T00:00:00.000Z')
        report = ds.drift(self.root, since='2026-09-30T07:00:00.000Z')
        self.assertEqual([i['key'] for i in report['changed']], ['test'])
        # Unchanged, but without a cell baseline: exported once to create one.
        self.assertEqual([i['key'] for i in report['baseline_refresh']], ['ref'])
        self.assertEqual(report['export'], ['test', 'ref'])
        self.assertEqual([f['id'] for f in report['new_files']], ['wb9'])

    def test_capture_delta_and_commit(self):
        new = json.loads(json.dumps(OLD))
        new['INPUTS']['B4'] = 'radiators glowing - after burns'
        self.observe('2026-09-30T08:00:00.000Z', wb1='2026-09-29T12:00:00.000Z')
        self.export('2026-09-30T08:01:00.000Z', new)
        result = ds.capture(self.root, 'references/cap', since='2026-09-30T07:00:00.000Z')
        self.assertEqual(result['workbooks'], ['test'])
        with self.assertRaises(FileExistsError):
            ds.capture(self.root, 'references/cap', since='2026-09-30T07:00:00.000Z')
        self.assertEqual(ds.delta(self.root, 'references/cap')['suggested_class'], 'EDITORIAL')
        ds.commit(self.root, 'references/cap', note='editorial')
        state = ds.load_state(self.root)['workbooks']['test']
        self.assertEqual(state['reviewed_modified_utc'], '2026-09-29T12:00:00.000Z')
        self.assertEqual(state['baseline']['path'], 'references/cap/test.xlsx')
        self.assertFalse(ds.is_stale(state))
        with self.assertRaisesRegex(ValueError, 'not open'):
            ds.commit(self.root, 'references/cap', note='again')

if __name__ == '__main__':
    unittest.main()
