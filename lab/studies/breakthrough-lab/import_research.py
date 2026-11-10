"""Versioned, read-only import of T00 and T05 research results into imports/<thread>-<commit>/ (research only, NOT canon).

The Vertex research lives on two unmerged branches whose heads may move. This copies named result files from one pinned commit of
each (git show, so no checkout and no change to either branch) and writes MANIFEST.json with the branch, the commit, each file's
path at that commit and its sha256. The website and the scenario grid read only these copies, so a later push to either branch
changes nothing here until someone re-imports a newer commit on purpose.

    python3 lab/studies/breakthrough-lab/import_research.py            # re-creates imports/ from the pinned commits below
"""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

IMPORTS = [
    {'thread': 'T00', 'name': 'Vertex T00 integration and feasibility gates 1 and 2', 'branch': 'claude/project-thread-9rsgog',
     'commit': '030fc14259e20eeeb224aa2c78dd06459c3afc7a', 'folder': 't00-030fc14', 'base': 'lab/variants/vertex-drive/',
     'files': ['registry/sources.toml', 'registry/technologies.toml', 'registry/generations.toml', 'results/convergence.json',
               'studies/gate/REPORT.md', 'studies/gate/results/coupled.json', 'studies/gate/results/target.json',
               'studies/gate/results/axis_base.json', 'studies/gate/results/structure.json', 'studies/gate/results/concepts.json',
               'studies/gate2/REPORT.md', 'studies/gate2/results/target2.json', 'studies/gate2/results/eta.json',
               'studies/gate2/results/matrix.json', 'studies/gate2/results/cone.json', 'studies/gate2/results/g1.json',
               'studies/gate2/results/validity.json']},
    {'thread': 'T05', 'name': 'Vertex T05 Blender blockout and feasibility gates 1 and 2', 'branch': 'claude/project-thread-ctwplp',
     'commit': 'f49777844782dd4aade5e1eb3834a8f832a4ba24', 'folder': 't05-f497778', 'base': 'work/vertex-blender/',
     'files': ['GATE_REPORT.md', 'fe_s5n.json', 'screen.json', 'GATE2_REPORT.md', 'gate2.json', 'gate2_fe.json']},
]


def git_show(commit, path):
    return subprocess.run(['git', 'show', f'{commit}:{path}'], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    for imp in IMPORTS:
        out = HERE / 'imports' / imp['folder']
        rows = []
        for rel in imp['files']:
            data = git_show(imp['commit'], imp['base'] + rel)
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            rows.append({'path': rel, 'source_path': imp['base'] + rel, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        manifest = {k: imp[k] for k in ('thread', 'name', 'branch', 'commit', 'folder', 'base')}
        manifest.update({'status': 'RESEARCH, NON-CANON, read-only snapshot', 'files': rows})
        (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1) + '\n')
        print(f"{imp['folder']}: {len(rows)} files from {imp['branch']} {imp['commit'][:7]}")


if __name__ == '__main__':
    main()
