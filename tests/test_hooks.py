"""Claude hook scripts: role guard, Python syntax check and Drive inbox (stdin JSON in, JSON out)."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / 'tools/hooks'
sys.path.insert(0, str(ROOT / 'tests'))
from test_drive_sync import xlsx, OLD


def call(script, event, root):
    result = subprocess.run([sys.executable, str(HOOKS / script)], input=json.dumps(event), text=True,
                            capture_output=True, env={**os.environ, 'CLAUDE_PROJECT_DIR': str(root)})
    return result.returncode, json.loads(result.stdout) if result.stdout.strip() else None, result.stderr


class DriveInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        (self.root / 'data/source_sync.json').write_text(json.dumps({'workbooks': {'t': {'id': 'wb1'}}}))

    def tearDown(self):
        self.temp.cleanup()

    def test_watched_export_is_kept_on_disk_and_replaced_by_a_summary(self):
        data = xlsx(OLD)
        response = json.dumps({'content': base64.b64encode(data).decode(), 'id': 'wb1',
                               'title': 'Any title', 'mimeType': 'application/xlsx'})
        event = {'tool_name': 'mcp__x__download_file_content', 'tool_input': {'fileId': 'wb1'},
                 'tool_response': response}
        code, output, _ = call('drive_inbox.py', event, self.root)
        self.assertEqual(code, 0)
        summary = json.loads(output['hookSpecificOutput']['updatedMCPToolOutput'])
        self.assertEqual((self.root / summary['xlsx']).read_bytes(), data)
        self.assertIn('===== SHEET INPUTS =====', (self.root / summary['txt']).read_text())
        self.assertLess(len(output['hookSpecificOutput']['updatedMCPToolOutput']), 1200)

    def test_unrelated_files_pass_through_untouched(self):
        response = json.dumps({'content': base64.b64encode(xlsx(OLD)).decode(), 'id': 'other', 'title': 'Budget'})
        event = {'tool_name': 'mcp__x__download_file_content', 'tool_input': {'fileId': 'other'},
                 'tool_response': response}
        self.assertEqual(call('drive_inbox.py', event, self.root)[1], None)
        self.assertFalse((self.root / 'runs').exists())

    def test_ignition_metadata_is_saved_for_drift(self):
        response = json.dumps({'id': 'new1', 'title': 'IGNITION — New', 'modifiedTime': '2026-09-30T00:00:00Z'})
        call('drive_inbox.py', {'tool_name': 'mcp__x__get_file_metadata', 'tool_response': response}, self.root)
        saved = list((self.root / 'runs/drive_inbox').glob('meta-*-new1.json'))
        self.assertEqual(len(saved), 1)


if __name__ == '__main__':
    unittest.main()
