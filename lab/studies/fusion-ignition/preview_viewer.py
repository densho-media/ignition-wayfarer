#!/usr/bin/env python3
"""Development preview only: add to a tools/wos.py preview site the viewer files the Fusion Ignition page fetches (vendor three.js,
the engine inspection manifest, its part meshes and the vacuum field file, exactly as tools/web_export.py writes them) without Blender
or the ship GLB. `python3 lab/studies/fusion-ignition/preview_viewer.py runs/fi-preview`."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/wayfarer')); sys.path.insert(0, str(ROOT / 'tools'))
import spec as S  # noqa: E402
import vertex_inspect  # noqa: E402
import vertex_magnet  # noqa: E402
import web_export  # noqa: E402

site = Path(sys.argv[1]).resolve(); viewer = site / 'viewer'; (viewer / 'model').mkdir(parents=True, exist_ok=True)
web_export.vendor_three(viewer)
s = S.load()[0]
inspect, geometry = vertex_inspect.manifest(s)
gf = f'model/engine-parts-{hashlib.sha256(geometry).hexdigest()[:12]}.bin'; (viewer / gf).write_bytes(geometry); inspect['geometry']['file'] = gf
ft = json.dumps(vertex_magnet.overlay(s), separators=(',', ':'))
ff = f'model/field-{hashlib.sha256(ft.encode()).hexdigest()[:12]}.json'; (viewer / ff).write_text(ft); inspect['magnet']['field_file'] = ff
et = json.dumps(inspect, separators=(',', ':'))
ef = f'model/engine-{hashlib.sha256(et.encode()).hexdigest()[:12]}.json'; (viewer / ef).write_text(et)
(viewer / 'build.json').write_text(json.dumps({'engine_file': ef, 'engine_parts_file': gf, 'preview': 'lab/studies/fusion-ignition/preview_viewer.py'}))
print('viewer files:', ef, gf, ff)
