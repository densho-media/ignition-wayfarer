"""`python3 tools/workflow.py play-characters --out DIR`: the characters the browser experiences need (LOCO-001/002, docs/LOCOMOTION.md),
built from tracked inputs on a clean checkout, for `workflow.py web --characters DIR`.

character loop without the in-vehicle fit (build/human.py -> rig review -> human_gltf.py -> Godot character check) -> EVA suit build
(build/eva_suit.py) -> drone (build/eva_drone.py) -> EVA system (build/eva_scene.py) -> EVA export (export/eva_gltf.py). DIR then holds
what the play package copies into generated/characters: the player (data/characters.toml [locomotion] player, its textures and
characters.json) and the Y155 instructor suit and the drone (eva_instructor.glb, eva_drone.glb, eva_characters.json). Nothing here
checks pressure coverage or the in-vehicle fit: that is `workflow.py eva` and `characters` with the fit, which this does not replace.
"""
import json
from pathlib import Path
import shutil
import subprocess
import time
import tomllib

import character_loop
import external
import pipeline

EVA_FILES = ('eva_instructor.glb', 'eva_drone.glb', 'eva_characters.json')


def run(root, out):
    t0 = time.monotonic()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    chars = character_loop.run(root, None, fit=False)
    if chars.get('result') != 'PASS':
        return dict(result='FAIL', step='characters', characters=chars)
    rd = root / chars['run_dir']
    player = tomllib.loads((root / 'data/characters.toml').read_text()).get('locomotion', {}).get('player', 'newcomer')
    for p in sorted((rd / 'glb').iterdir()):
        if p.name == 'characters.json' or p.name.startswith(player + '.') or p.name.startswith(player + '_'):
            shutil.copy2(p, out / p.name)
    eva = rd / 'eva'
    eva.mkdir()
    seconds = {}
    env = external.blender_env()
    for name, argv in [('eva-build', pipeline.blender(root / 'src/wayfarer/build/eva_suit.py', '--report', eva / 'p1_eva_suit.json')),
                       ('eva-drone', pipeline.blender(root / 'src/wayfarer/build/eva_drone.py')),
                       ('eva-system', pipeline.blender(root / 'src/wayfarer/build/eva_scene.py')),
                       ('eva-export', pipeline.blender(root / 'src/wayfarer/export/eva_gltf.py', '--out', eva))]:
        log = rd / f'{name}.log'
        s = time.monotonic()
        with open(log, 'w') as f:
            code = subprocess.run([str(a) for a in argv], cwd=root, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=pipeline.STEP_TIMEOUT).returncode
        seconds[name] = round(time.monotonic() - s, 1)
        if code:
            return dict(result='FAIL', step=name, log=str(log.relative_to(root)), tail=pipeline.failure_tail(log))
    for name in EVA_FILES:
        shutil.copy2(eva / name, out / name)
    files = {p.name: p.stat().st_size for p in sorted(out.iterdir())}
    return dict(result='PASS', run_dir=chars['run_dir'], player=player, out=str(out), files=files, mb=round(sum(files.values()) / 1e6, 1),
                seconds=dict(chars['seconds'], **seconds, total=round(time.monotonic() - t0, 1)))
