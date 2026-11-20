"""Assemble the browser review page of Vertex 1.8 Phase F (work, not canon): review_template.html + the GLBs from export_glb.py + the
timeline from aplus.py, one self-contained HTML file.

  python3 lab/studies/vertex-closure/vertex-1-8/build_page.py            # runs/vtx18_web/vtx18_review.html (three.js from jsdelivr, for publication)
  python3 lab/studies/vertex-closure/vertex-1-8/build_page.py --local    # runs/vtx18_web/local/index.html (vendored three.js, for the measurements)
"""
import base64
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import aplus  # noqa: E402
import vertex_cluster as vc  # noqa: E402

WEB = ROOT/'runs'/'vtx18_web'


def data(measure_text, raw=False):
    s, R = aplus.load(); doc = aplus.write(s, R); T = aplus.timeline(s, R)
    glb = {k: base64.b64encode((WEB/f'{k}{"_raw" if raw else ""}.glb').read_bytes()).decode() for k in ('aplus', 'baseline', 'effects')}
    dirs = {}
    for L in ('L1', 'L2'):
        for j in range(1, 9):
            sh, ar = aplus.petal_motion(s, f'PETAL_{L}_{j}'); dirs[f'{L}_{j}'] = dict(shell=sh, armour=ar)
    pls = [dict(n=p['n'], origin=p['origin'], axes=p['axes']) for p in vc.placements(s)]
    shots = aplus.SHOTS
    return dict(timeline=doc['timeline'], samples=doc['samples'], effects=doc['effects'], fps=doc['fps'], field_lines=doc['field_lines'],
                open=doc['open'], glb=glb, petal_dirs=dirs, placements=pls, shots=shots, diag=T['diagnostics'], proto=aplus.PROTO,
                measure_text=measure_text)


def build(local=False, measure_text='(measurements: see the study Doc)'):
    html = (HERE/'review_template.html').read_text()
    html = html.replace('__DATA__', json.dumps(data(measure_text, raw=not local), separators=(',', ':')).replace('</', '<\\/'))
    if local:
        html = html.replace('https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js', './three/three.module.min.js')
        html = html.replace('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/', './three/addons/')
        html = html.replace('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/', './three/draco/')
        html = html.replace("'./three/addons/libs/draco/gltf/'", "'./three/draco/'")
        out = WEB/'local'; out.mkdir(parents=True, exist_ok=True)
        src = sorted(ROOT.glob('runs/*-web/site/viewer/vendor/three'))[-1]
        if not (out/'three').exists():
            shutil.copytree(src, out/'three')
        (out/'index.html').write_text(html)
        return out/'index.html'
    import re
    for pat in (r'<!doctype html>\s*', r'<html[^>]*>\s*', r'</html>\s*', r'<head>\s*', r'</head>\s*', r'<body>\s*', r'</body>\s*',
                r'<meta charset="utf-8">\s*', r'<meta name="viewport"[^>]*>\s*'):
        html = re.sub(pat, '', html, count=1)
    fp = WEB/'vtx18_review.html'; fp.write_text(html)
    return fp


if __name__ == '__main__':
    mt = (WEB/'measure.txt').read_text() if (WEB/'measure.txt').exists() else '(measurements: see the study Doc)'
    fp = build('--local' in sys.argv, mt)
    print(fp, fp.stat().st_size)
