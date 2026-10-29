"""FUT-002: build the example shots in shots/shots.toml into shots/<name>.blend, and optionally render review frames.

Shot files are generated: a rebuild replaces a shot file wholesale, and refuses a file that is not a generated shot of
the same name. Hand-made shot work belongs in its own file that links a generated shot. The assets are only read.
"""
import argparse
import sys
from pathlib import Path
import bpy
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/shots')]
import representation as rp
import shot_tools


def build_one(root, name, config, size):
    path = root/'shots'/f'{name}.blend'
    if path.exists():
        bpy.ops.wm.open_mainfile(filepath=str(path))
        if bpy.context.scene.get('wf_shot') != name or bpy.context.scene.get('wf_owner') != shot_tools.OWNER:
            raise RuntimeError(f'{path} is not a generated {name} shot; refusing to replace it')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, items, tables, objects = shot_tools.build(root, name, config['shot'][name], config, size)
    shot_tools.save(path)
    print(f'WF_SHOT {name} {len(objects)} objects, {len({i["group"] for i in items})} groups -> {path.relative_to(root)}', flush=True)
    return path


def render(root, name, config, frames, size, out_dir=None):
    bpy.ops.wm.open_mainfile(filepath=str(root/'shots'/f'{name}.blend'))
    scene = bpy.context.scene
    shot_tools.render_settings(scene, scene['representation'], size)
    out = out_dir or root/'runs/renders/shots'/name; out.mkdir(parents=True, exist_ok=True)
    for frame in frames or config['shot'][name]['review_frames']:
        scene.frame_set(frame); scene.render.filepath = str(out/f'{name}_f{frame:04}.png')
        bpy.ops.render.render(write_still=True)
        print(f'WF_SHOT_RENDER {name} {frame}', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--shots', nargs='+')
    p.add_argument('--render', action='store_true'); p.add_argument('--render-only', action='store_true')
    p.add_argument('--frames', nargs='+', type=int); p.add_argument('--size', type=int, default=768)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not 128 <= a.size <= 1920:
        raise ValueError('Use 128-1920 px shot renders')
    root = a.root.resolve(); config = rp.load_shots(root)
    for name in a.shots or list(config['shot']):
        if name not in config['shot']:
            raise KeyError(f'Unknown shot {name}')
        if not a.render_only:
            build_one(root, name, config, a.size)
        if a.render or a.render_only:
            render(root, name, config, a.frames, a.size)
