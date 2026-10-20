"""PostToolUse hook: keep Drive connector results for Wayfarer sources on disk.

Matches the connector's metadata, search and download tools. Only files watched
in `data/source_sync.json` or titled "IGNITION …" are touched; everything else
passes through unchanged.

- Metadata/search responses are saved as `runs/drive_inbox/meta-<utc>-<id>.json`
  so `tools/workflow.py drift` compares exact timestamps instead of numbers an
  agent copied by hand.
- A workbook export (xlsx, base64 in the response) is written to
  `runs/drive_inbox/export-<id>-<sha>.{xlsx,txt,json}` and the model sees a short
  summary instead of tens of thousands of base64 tokens. `workflow.py capture`
  later turns those files into evidence.
Fails open: any error leaves the original tool output untouched.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drive_sync  # noqa: E402  (stdlib-only module next to this package)


def relevant(file_id, title, watched):
    return file_id in watched or 'IGNITION' in (title or '').upper()


def shaped(summary, response):
    """Mirror the tool's output shape: content blocks, a dict, or text."""
    text = json.dumps(summary, ensure_ascii=False)
    if isinstance(response, list):
        return [{'type': 'text', 'text': text}]
    if isinstance(response, dict):
        return summary
    return text


def handle(event, root):
    tool = event.get('tool_name', '')
    response = event.get('tool_response')
    state_path = root / drive_sync.STATE
    watched = set()
    if state_path.exists():
        watched = {w['id'] for w in json.loads(state_path.read_text())['workbooks'].values()}
    inbox = root / drive_sync.INBOX
    now = datetime.now(timezone.utc)
    saved_at = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    if tool.endswith('__download_file_content'):
        file_id = event.get('tool_input', {}).get('fileId', '')
        data, meta = drive_sync.export_bytes(response)
        if not data or data[:2] != b'PK' or not relevant(file_id, meta.get('title'), watched):
            return None
        sheets = drive_sync.read_xlsx(data)
        digest = hashlib.sha256(data).hexdigest()
        inbox.mkdir(parents=True, exist_ok=True)
        base = inbox / f'export-{file_id}-{digest[:12]}'
        base.with_suffix('.xlsx').write_bytes(data)
        base.with_suffix('.txt').write_text(drive_sync.dump_text(sheets))
        record = {'fileId': file_id, 'title': meta.get('title'), 'mimeType': meta.get('mimeType'),
                  'sha256': digest, 'bytes': len(data), 'sheets': len(sheets), 'saved_at': saved_at}
        base.with_suffix('.json').write_text(json.dumps(record, indent=1, ensure_ascii=False) + '\n')
        summary = {**record, 'saved_by': 'tools/hooks/drive_inbox.py',
                   'xlsx': str(base.with_suffix('.xlsx').relative_to(root)),
                   'txt': str(base.with_suffix('.txt').relative_to(root)),
                   'note': 'Workbook bytes kept on disk instead of in context; next: '
                           'python3 tools/workflow.py capture <capture_dir> --since <run start>.'}
        return {'hookSpecificOutput': {'hookEventName': 'PostToolUse',
                                       'updatedMCPToolOutput': shaped(summary, response)}}
    records = list(drive_sync.metadata_records(response))
    hits = [r for r in records if relevant(r['id'], r.get('title'), watched)]
    if hits:
        inbox.mkdir(parents=True, exist_ok=True)
        name = f'meta-{now.strftime("%Y%m%dT%H%M%S%fZ")}-{hits[0]["id"]}.json'
        (inbox / name).write_text(json.dumps({'saved_at': saved_at, 'tool': tool, 'response': response},
                                             ensure_ascii=False) + '\n')
    return None


def main():
    try:
        event = json.load(sys.stdin)
        root = Path(os.environ.get('CLAUDE_PROJECT_DIR') or event.get('cwd') or '.').resolve()
        if (root / drive_sync.INBOX / '.debug').exists():  # opt-in trace of raw hook input
            trace = root / drive_sync.INBOX / f'debug-{datetime.now(timezone.utc).strftime("%H%M%S%f")}.json'
            trace.write_text(json.dumps({k: (v if k != 'tool_response' else str(v)[:2000]) for k, v in event.items()},
                                        ensure_ascii=False, default=str))
        output = handle(event, root)
    except Exception as error:
        print(f'drive_inbox hook error (ignored): {error}', file=sys.stderr)
        return 0
    if output:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
